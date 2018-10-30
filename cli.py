import os.path
import glob
import multiprocessing
import re

import click


_column = re.compile(
    "\w{3}[&=]\d+"
    "(?P<lemma>[A-Z]+)\s+"
    "(?P<lemma_nb>\d)?"
    "(<\w+>\s)?"  # ???
    "(?P<token>(in )?[\w\.]+)"
    "(\s[<\(]\w+[>\)])?\s+"  # ???
    "[\d,]+\s+"
    "(?P<morph>([A-Z][0-9 \*]+)|#)"
    "(?P<pos>[A-Z][0-9]?)?")

_lemma = re.compile("\w{3}[&=]\d+([A-Z]+)\s+(\w?)")


def parse_line(line: str) -> dict:
    line = line.replace("\n", "")
    if not line.strip():
        return None
    lemma, lemma_n = _lemma.match(line[:30]).groups()
    form = line[30:55].strip()
    _ = line[55:67]
    morph = line[67:78]
    pos = line[78:].replace(" ", "") or morph[0]

    return {"lemma": lemma, "lemma_n": lemma_n, "form": form, "morph": morph, "pos": pos}


def convert_apn(file, transform_morph=False):
    print("Treating " + file)
    content = "form\tlemma\tmorph\tpos\n"
    with open(file) as f:
        for line in f.readlines():
            try:
                annotation = parse_line(line)
            except Exception as E:
                print(file, line)
                raise E

            # If we were able to parse
            if annotation:

                # If we want to transform the morph to another format
                if transform_morph:
                    annotation["morph"] = None

                content += "\t".join([
                    annotation["form"],
                    annotation["lemma"]+annotation["lemma_n"],
                    annotation["morph"],
                    annotation["pos"]
                ])+"\n"

    return {"path": file, "content": content}


def convert_apn_light(file: str) -> dict:
    return convert_apn(file, False)


def write(path, content, output):
    print(path, content[0:100], output)


@click.command()
@click.argument("source", type=click.Path(exists=True))
@click.argument("output", type=click.Path(exists=False))
@click.option("--threads", type=click.INT)
def cli(source, output, threads=1):
    # First, we move from the input to a list of files
    # If this is a single file, we put it in a list, otherwise we retrieve all .APN files
    input_files = [source]
    if os.path.isdir(source):
        input_files = glob.glob(os.path.join(source, "*.APN"), recursive=True)

    # Process as threads
    with multiprocessing.Pool(processes=threads) as pool:
        for item in pool.imap_unordered(convert_apn_light, iterable=input_files):
            write(output=output, **item)


if __name__ == '__main__':
    cli()
