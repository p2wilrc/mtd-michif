var config = {
  L1: {
    name: 'Michif',
    lettersInLanguage: [
      'a',
      'b',
      'c',
      'd',
      'e',
      'f',
      'g',
      'h',
      'i',
      'j',
      'k',
      'l',
      'm',
      'n',
      'o',
      'p',
      'q',
      'r',
      's',
      't',
      'u',
      'v',
      'w',
      'x',
      'y',
      'z'
    ],
    transducers: {
      'michif-approx': [
        { ae: 'a' },
        { aw: 'a' },
        { uh: 'a' },
        { ay: 'e' },
        { ee: 'e' },
        { oo: 'u' },
        { ou: 'u' },
        { au: 'u' },
        { uw: 'u' },
        { hk: 'k' },
        { ht: 't' },
        { hp: 'p' },
        { '\\-': '' },
        { '\u2019': '' },
        { "'": '' }
      ]
    }
  },
  L2: { name: 'English' },
  build: '202306141529',
  audio_path: 'assets/'
};
