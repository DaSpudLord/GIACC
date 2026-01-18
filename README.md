# GIACC
Miliastra Wonderland Asset Classic Converter

By default, Genshin Impact's Miliastra Editor does not allow importing assets created in Beyond Mode into Classic Mode, or vice versa. However, this restriction can be bypassed by [manually editing the bytes in the asset file](https://docs.google.com/document/d/1xQaifTrkP4zjyW1QFnB5tCJFuu9D50qkf0QnbaQTSaQ/edit?tab=t.0#heading=h.e49gh4hdgqwv). This repo provides a simple Python script to automate those edits.

## Usage

The script runs in a command line. You will need [Python](https://www.python.org/) installed to run it.

To convert an asset, open a shell to the repository and enter one of the following commands:
```
python giacc.py to-classic [input filename] [output filename]
python giacc.py to-beyond [input filename] [output filename]
```
Replace `[input filename]` with the name of the GIA file to be converted, and `[output filename]` to the location where the converted result will be placed. Alternatively, `*` can be used in place of the `[output filename]` to write the converted result back to the input file. The first form will convert to Classic Mode, and the second form will convert to Beyond Mode.

The script can also be used to just check an asset's mode:
```
python giacc.py query [filename]
```
Tests whether `[filename]` denotes a Classic Mode or Beyond Mode asset file.

Information on how to use the script can be obtained by:
```
python giacc.py help
```