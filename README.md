# Electronic version of the Turtle Mountain Michif Dictionary

This repository contains the scripts needed to prepare the data files
for the Turtle Mountain dictionary of Michif, along with the
Progressive Web App frontent itself.

## Software Requirements

The dictionary build requires Python 3.9 or newer. If you don't have
this the easiest thing to do is to install
[Anaconda](https://www.anaconda.com/download).

It also requires SoX with FLAC and MP3 support, which can be done on
Ubuntu with:

    sudo apt-get install sox libsox-fmt-all

Or under Anaconda with:

    conda install -c conda-forge sox

Now install the dictionary building tools in a "virtual environment":

    python -m venv venv && . venv/bin/activate
    pip install -e .

To verify that it works, you can run the test suite:

    pip install pytest
    pytest

You will need [Node.js 18](https://nodejs.org/en) to build the web
front-end. You can install the dependencies with:

    npm install

## Data Requirements

Building the actual dictionary requires:

- the metadata spreadsheet with session and speaker metadata
- the (revised and cleaned up) text format dictionary
- the annotations for the audio recordings
- the original recordings

While the source code for building the dictionary is freely
distributable under an open-source license, the data is not. Please
contact [P2WILRC](mailto:info@p2wilr.org) if you wish to access the
data for research purposes.

The data is available as two separate components:
`mtd-michif-annotations`, which contains the metadata, text, and ELAN
format annotations, and `mtd-michif-recordings`, which is the audio
recordings themselves. This repository contains a tiny sample of the
full data for testing purposes.

# Building the dictionary

To build the dictionary, we assume that you have
`mtd-michif-annotations` and `mtd-michif-recordings` in the same
parent directory as this repository. Assuming you have installed
everything as mentioned above, you can then simply run:

    mtd-michif

Once this has succeeded, you can launch the website locally with:

    npm start

And follow the instructions (it should be available at
[http://locahost:4200](http://locahost:4200))

To build the application in `dist/mtd`:

    npm run build

If you want to deploy it in a subdirectory of your web server
(e.g. `https://my.awesome.site/michif-web/`) then you can use the
`--base-href` flag to `ng build`:

    npx ng build --configuration production --base-href /michif-web/

## Acknowledgements

MTD-UI has had significant help from a huge number of people including
but not limited to Patrick Littell, Mark Turin, & Lisa Matthewson.

As well as institutional support from the [First Peoples' Cultural
Council](http://www.fpcc.ca/) and SSHRC Insight Grant 435-2016-1694,
‘Enhancing Lexical Resources for BC First Nations Languages’.

## License

© 2023 Prairies to Woodlands Indigenous Language Revitalization Circle
and Aidan Pine. [MIT license](LICENSE)
