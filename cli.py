#!/usr/bin/env python3

import os.path
import glob
import multiprocessing
import re
import typing
import argparse


_lemma = re.compile("\w{3}[&=]\d+([A-Z]+)\s+(\w?)")
_sent = re.compile("\w{3}[&=](\d+)")
_token = re.compile(
    "(<\w+>\s)?"  # ???
    "(?P<token>(in )?[\w\.]+)"
    "(\s[<\(]\w+[>\)])?"
)

remove_added = re.compile("(\s?[<\(]\w+[>\)]\s?)")


class Parser:
    def __init__(self,
                 transform_morph: bool = True, no_disambiguation: bool = False, bpn: bool = False,
                 lowercase: bool = False):
        """

        :param transform_morph: Morphological information transformation
        :param no_disambiguation: Removes `_\w` from the lemma information
        :param bpn: Whether the parser parse BPN
        :param lowercase: Moves lemma to lowercase
        """
        self.transform_morph = transform_morph
        self.no_disambiguation = no_disambiguation
        self.bpn = bpn
        self.lowercase = lowercase

    @staticmethod
    def bpn_line(line: str) -> typing.Optional[dict]:
        """ Parse a single line into each information

        :param line: Input line from APN
        :return: Dictionary representing the information about the token
        """
        line = line.replace("\n", "")
        if not line.strip() or line.endswith("#            "):
            return None
        connection_sign = line[3]
        if connection_sign == "#":  # Forme de contraction, présent à partir du deuxième lemme
            return None  # At the moment, let's not care about it
        elif connection_sign == "=":  # QUE : doit être collé au précédent
            return None  # At the moment, let's not care about it
        elif connection_sign == "&":
            write = True

        lemma, lemma_n = line[8:29].strip(), line[29]
        sent = line[4:8]
        form = line[30:55].strip()
        form = remove_added.sub("", form)

        if lemma != "#":  # Which is used for Greek words
            morph = line[67:77]
            pos = line[78:].replace(" ", "") or morph[0]
        else:
            morph = ""
            pos = ""

        return {"lemma": lemma, "lemma_n": lemma_n, "form": form, "morph": morph, "pos": pos,
                "new": sent}

    @staticmethod
    def apn_line(line: str) -> typing.Optional[dict]:
        """ Parse a single line into each information

        :param line: Input line from APN
        :return: Dictionary representing the information about the token
        """
        line = line.replace("\n", "")
        if not line.strip():
            return None
        lemma, lemma_n = _lemma.match(line[:30]).groups()
        sent, *_ = _sent.match(line[:30]).groups()
        form = _token.sub("\g<token>", line[30:55].strip())
        _ = line[55:67]
        morph = line[67:78]
        pos = line[78:].replace(" ", "") or morph[0]

        return {"lemma": lemma, "lemma_n": lemma_n, "form": form, "morph": morph, "pos": pos,
                "new": sent}

    def __call__(self, file):
        """ Take a single file path and transform the data into
            a new TSV file

            :param file: File to read
            :return: Dict with "content" for String representation of the TSV conversion and "file" for original filepath
            """
        print("Treating " + file)
        error = []
        content = "form\tlemma\tmorph\tpos\tindex\n"

        # Choose line parser
        line_parser = self.apn_line
        if self.bpn:
            line_parser = self.bpn_line

        with open(file) as f:
            last = False
            try:
                for line in f.readlines():
                    try:
                        annotation = line_parser(line)
                    except Exception as E:
                        error.append(line)
                        raise E

                    # If we were able to parse
                    if annotation:

                        # If we want to transform the morph to another format
                        if self.transform_morph:
                            if annotation["morph"] != "":  # Safe keeping against empty morph
                                annotation.update(convert_morph(annotation["morph"]))
                                if "ERROR|" in annotation["morph"]:
                                    error.append(line)
                                    annotation["morph"] = annotation["morph"].replace("ERROR|", "")

                        lemma = annotation["lemma"] + "_" + annotation["lemma_n"]
                        if self.no_disambiguation:
                            lemma = lemma.split("_")[0]

                        if self.lowercase:
                            lemma = lemma.lower()

                        if annotation["new"] != last and last != False:
                            content += "\n"

                        content += "\t".join([
                            annotation["form"],
                            lemma,
                            annotation["morph"],
                            annotation["pos"],
                            annotation["new"]
                        ]) + "\n"

                        last = annotation["new"]

            except Exception as E:
                error.append(line)

        return {"path": file, "content": content, "error": error}


_cat = {
    "A": ("NOM", lambda x: ""),
    "B": ("VER", lambda x: ""),
    "C": ("ADJ", lambda x: "qua"+""),
    "D": ("ADJ", {"1": "car", "2": "ord", "3": "dis", "4": "mul", "5": "adv.ord", "6": "adv.mul"}),
    "E": ("PROper", None),
    "F": ("PROpos", None),
    "G": ("PROref", None),  # Not in CATEX obviously. Could be PROper
    "H": ("PROpos.ref", None),
    "I": ("PROdem", None),
    "J": ("PROrel", None),
    "K": ("PROint", None),
    "L": ("PROind", None),
    "M": ("ADV", None),
    "N": ("ADVrel", None),
    "O": ("ADVint", None),
    "P": ("ADVneg", None),
    "Q": ("ADVint.neg", None),
    "R": ("PRE", None),
    "S": ("CONcoo", None),
    "T": ("CONsub", None),
    "U": ("INJ", None),
    "#": ("VERaux", None),
    "0": ("", None)
}


def convert_pos(pos: str) -> str:
    """ Convert the POS tag

    :param pos: POS code from APN
    :return: Converted POS
    """
    cat, subcat = pos[0], pos[1]
    POS, fn_subcat = _cat[cat]
    if fn_subcat:
        if isinstance(fn_subcat, typing.Callable):
            POS += fn_subcat(subcat)
        elif isinstance(fn_subcat, dict):
            POS += fn_subcat[subcat]
    return POS


_morphs = [
    {   # Case
        "1": "Case=Nom",
        "2": "Case=Voc",
        "3": "Case=Acc",
        "4": "Case=Gen",
        "5": "Case=Dat",
        "6": "Case=Abl",
        "7": "Case=Loc",
        "8": "Case=Ind"
    },
    {   # Nombre
        "1": "Numb=Sing",
        "2": "Numb=Plur"
    },
    {   # Degré
        "1": "Deg=Pos",
        "2": "Deg=Comp",
        "3": "Deg=Sup"
    },
    {   # Mode
        "0": "ERROR",  # Ignore (We had one for an agendis annotation)
        "1": "Mood=Ind",
        "2": "Mood=Sub",
        "3": "Mood=Imp",
        "4": "Mood=Par",
        "7": "Mood=Inf",
        "5": "Mood=Adj",
        "6": "Mood=Ger",
        "8": "Mood=SupU",
        "9": "Mood=SupUm",
    },
    {   # Temps
        "0": "ERROR",  # Ignore (We had one for an agendis annotation)
        "1": "Tense=Pres",
        "2": "Tense=Impa",
        "3": "Tense=Fut",
        "4": "Tense=Perf",
        "5": "Tense=Pqp",
        "6": "Tense=Fut",
        "7": "Tense=PeriPerf",
        "8": "Tense=PeriPqp",
        "9": "Tense=PeriFut"
    },
    {   # Voix
        "1": "Voice=Act",
        "2": "Voice=Pass",
        "3": "Voice=Dep",
        "4": "Voice=SemDep"
    },
    {   # Pers
        "1": "Person=1",
        "2": "Person=2",
        "3": "Person=3"
    }
]

_readable_vb = x = [
    [
        "Singulier",
        "Pluriel"
    ], [
        "Indicatif",
        "Subjonctif",
        "Impératif",
        "Participe",
        "Infinitif",
        "Adjectif verbal",
        "Gérondif",
        "Supin en -UM",
        "Supin en -U"
    ], [
        "Présent",
        "Imparfait",
        "Futur",
        "Parfait",
        "Plus-que-parfait",
        "Futur antérieur",
        "Périphrase au parfait",
        "Périphrase au plus-que-parfait",
        "Périphrase au futur antérieur"
    ], [
        "Actif",
        "Passif",
        "Déponent",
        "Semi-déponent"
    ], [
        "1re pers",
        "2e pers",
        "3e pers"
    ]
]


def convert_morph(morph_code: str) -> typing.Dict[str, str]:
    pos, morph = morph_code[:2], morph_code[2:9]
    morph = [
        _morphs[index][morph_char]
        for index, morph_char in enumerate(morph)
        if morph_char.strip()
    ]
    if not morph:
        morph = ["MORPH=EMPTY"]
    return {"pos": convert_pos(pos), "morph": "|".join(morph)}


def write(path: str, content: str, output: str, extension: str = "APN", error: typing.List[str] = None) -> None:
    """ Writes the converted content to the new file given path and output

    :param path: Path of the current file
    :param content: Content to be written
    :param output: Directory containing the output
    :param extension: Extension to write to
    :param error: List of errors that happened
    """
    filename = os.path.basename(path).replace("."+extension, ".tsv")
    target = os.path.join(output, filename)
    with open(target, "w") as f:
        f.write(content)
    if error:
        with open(os.path.join(output, "error.txt"), "a") as f:
            f.write("\n".join([""] + [filename+"\t\t"+err.strip() for err in error]))


def cli(source: str, output: str, threads: int = 1, enhanced_morph: bool=False,
        bpn: bool=False, no_disambiguation: bool = False, lowercase : bool = False):
    """ Convert APN/BPN files in source dir to tabular data in output dir

    :param source: A folder path as string containing APN/BPN
    :param output: Output folder for the transformation
    :param threads: Number of threads to user for the conversion
    :param enhanced_morph: Enhance the morphological information
    :param bpn: Search and parse BPN instead of APN
    :param no_disambiguation: Remove disambiguation from lemma
    :param lowercase: Lowercase the lemma value
    """
    extension = "APN"
    if bpn:
        extension = "BPN"
    # First, we move from the input to a list of files
    # If this is a single file, we put it in a list, otherwise we retrieve all .APN files
    input_files = [source]
    if os.path.isdir(source):
        input_files = glob.glob(os.path.join(source, "*."+extension), recursive=True)

    # Create directory
    os.makedirs(output, exist_ok=True)

    bpn = extension == "BPN"
    convert_fn = Parser(transform_morph=enhanced_morph, bpn=bpn,
                        no_disambiguation=no_disambiguation, lowercase=lowercase)

    # Process as threads
    with multiprocessing.Pool(processes=threads) as pool:
        for item in pool.imap_unordered(convert_fn, iterable=input_files):
            write(output=output, extension=extension, **item)


def morph_to_tsv():
    def loop_string(codes=None, readable=None, remaining_code=None, remaining_readable=None):
        codes = codes or list()
        readable = readable or list()

        for index, code in enumerate(remaining_code[0].values()):
            new_code = codes + [code]
            new_readable = readable + [remaining_readable[0][index]]
            if len(remaining_code) == 1:
                yield ["|".join(new_code),
                       " ".join([new_readable[index]
                                 for index in [4, 0, 1, 2, 3]])]
            else:
                yield from loop_string(new_code, new_readable, remaining_code[1:], remaining_readable[1:])

    rearranged_codes = [_morphs[1], _morphs[3], _morphs[4], _morphs[5], _morphs[6]]
    rearranged_readable = _readable_vb

    for c, r in loop_string(remaining_code=rearranged_codes, remaining_readable=rearranged_readable):
        yield c + "\t" + r


if __name__ == '__main__':
    arg = argparse.ArgumentParser(description="Converter of LASLA APN to TSV")
    arg.add_argument("source", help="Source file or directory (Must contain .APN"
                                    " files)")
    arg.add_argument("output", help="Output directory where new files will be saved")
    arg.add_argument("--bpn", help="Activate BPN parsing instead of APN", action="store_true", default=False)
    arg.add_argument("--threads", type=int, help="Number of threads to use")
    arg.add_argument("--enhanced_morph", action="store_true", default=False,
                     help="Replace morphology tags from LASLA with more conventional ones")
    arg.add_argument("--no-disambiguation", dest="no_disambiguation", action="store_true", default=False,
                     help="Does not keep lemma disambiguation")
    arg.add_argument("--lowercase", dest="lowercase", action="store_true", default=False,
                     help="Lowercase the lemma value")
    args = arg.parse_args()
    cli(args.source, args.output, args.threads, args.enhanced_morph, bpn=args.bpn,
        no_disambiguation=args.no_disambiguation, lowercase=args.lowercase)
