# Turtle Mountain Michif Dictionary Web UI

MTD is the second of two open-source tools that allow language
communities and developers to quickly and inexpensively make their
dictionary data digitally accessible. MTD-UI is a tool that visualizes
dictionary data that is prepared with
[MTD](https://github.com/roedoejet/mothertongues). This is a web
version constructed for the Michif language.

Please visit the [website](https://www.mothertongues.org) or
[docs](https://mother-tongues-dictionaries.readthedocs.io/en/latest/)
for more information.

## Requirements

You should have [Node.js 18](https://nodejs.org/en) installed. Now
you can install the dependencies with:

    npm install

To run a local development server:

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

This version of MTD Web UI was built using the _incredible_ [Angular
NgRx
starter](https://github.com/tomastrajan/angular-ngrx-material-starter)
by Tomas Trajan. If you're an Angular developer, go check it out!

## License

[MIT © Aidan Pine.](LICENSE)
