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


def parse_line(line: str, last_sent: str) -> dict:
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


def convert_apn(file, transform_morph=True):
    print("Treating " + file)
    content = "form\tlemma\tmorph\tpos\tindex\n"
    with open(file) as f:
        last = False
        for line in f.readlines():
            try:
                annotation = parse_line(line, last)
            except Exception as E:
                print(file, line)
                raise E

            # If we were able to parse
            if annotation:

                # If we want to transform the morph to another format
                if transform_morph:
                    annotation.update(convert_morph(annotation["morph"]))

                content += "\t".join([
                    annotation["form"],
                    annotation["lemma"]+annotation["lemma_n"],
                    annotation["morph"],
                    annotation["pos"],
                    annotation["new"]
                ])+"\n"

                if annotation["new"] != last and last != False:
                    content += "\n"

                last = annotation["new"]

    return {"path": file, "content": content}


def convert_apn_light(file: str) -> dict:
    """ Convert an APN file without changing the Morph code

    :param file: Path to the file to be read
    :return: Dictionary containing the name of the file (`path`)
             and the converted `content`
    """
    return convert_apn(file, False)


_cat = {
    "A": ("NOM", lambda x: x),
    "B": ("VER", lambda x: x),
    "C": ("ADJ", lambda x: "qua"+x),
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
        "1": "Mood=Ind",
        "2": "Mood=Sub",
        "3": "Mood=Imp",
        "4": "Mood=Par",
        "5": "Mood=Inf",
        "6": "Mood=Adj",
        "7": "Mood=Ger",
        "8": "Mood=SupU",
        "9": "Mood=SupUm",
    },
    {   # Temps

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


def write(path: str, content: str, output: str) -> None:
    """ Writes the converted content to the new file given path and output

    :param path: Path of the current file
    :param content: Content to be written
    :param output: Directory containing the output
    """
    filename = os.path.basename(path).replace(".APN", ".tsv")
    target = os.path.join(output, filename)
    with open(target, "w") as f:
        f.write(content)


def cli(source, output, threads=1, enhanced_morph=False):
    # First, we move from the input to a list of files
    # If this is a single file, we put it in a list, otherwise we retrieve all .APN files
    input_files = [source]
    if os.path.isdir(source):
        input_files = glob.glob(os.path.join(source, "*.APN"), recursive=True)

    # Create directory
    os.makedirs(output, exist_ok=True)

    if enhanced_morph:
        convert_fn = convert_apn
    else:
        convert_fn = convert_apn_light

    # Process as threads
    with multiprocessing.Pool(processes=threads) as pool:
        for item in pool.imap_unordered(convert_fn, iterable=input_files):
            write(output=output, **item)


if __name__ == '__main__':
    arg = argparse.ArgumentParser(description="Converter of LASLA APN to TSV")
    arg.add_argument("source", help="Source file or directory (Must contain .APN"
                                    " files)")
    arg.add_argument("output", help="Output directory where new files will be saved")
    arg.add_argument("--threads", type=int, help="Number of threads to use")
    arg.add_argument("--enhanced_morph", action="store_true", default=False,
                     help="Replace morphology tags from LASLA with more conventional ones")
    args = arg.parse_args()
    cli(args.source, args.output, args.threads, args.enhanced_morph)
