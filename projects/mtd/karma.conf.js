// Karma configuration file, see link for more information
// https://karma-runner.github.io/1.0/config/configuration-file.html

module.exports = function(config) {
  var isWatch = config.buildWebpack.options.watch;
  config.set({
    files: [
      {
        pattern: 'src/assets/js/config*.js',
        watched: false,
        included: true,
        served: true,
        nocache: false
      },
      {
        pattern: 'src/assets/js/dict_cached*.js',
        watched: false,
        included: true,
        served: true,
        nocache: false
      },
      {
        pattern: 'src/assets/js/mtd-ui.min.js',
        watched: false,
        included: true,
        served: true,
        nocache: false
      }
    ],
    basePath: '',
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
    plugins: [
      require('karma-jasmine'),
      require('karma-chrome-launcher'),
      require('karma-jasmine-html-reporter'),
      require('karma-spec-reporter'),
      require('karma-coverage-istanbul-reporter'),
      require('@angular-devkit/build-angular/plugins/karma')
    ],
    client: {
      clearContext: false // leave Jasmine Spec Runner output visible in browser
    },
    coverageIstanbulReporter: {
      dir: require('path').join(__dirname, '../../coverage/mtd'),
      reports: ['html', 'lcovonly', 'text-summary'],
      fixWebpackSourcePaths: true
    },
    reporters: ['spec'],
    port: 9876,
    colors: true,
    logLevel: config.LOG_INFO,
    autoWatch: true,
    browsers: ['Chrome'],
    restartOnFileChange: true,
    browserNoActivityTimeout: 50000,
    singleRun: !isWatch
  });
};
