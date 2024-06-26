import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Config, DictionaryData } from '../models';
import { environment } from '../../../environments/environment';
import { META } from '../../../config/config';
import { uniq } from 'lodash';
// import { AlertController } from '@ionic/angular';

// Not sure exactly how to inject this in headless testing
var TESTCONFIG: Config = {
  L1: {
    name: 'foo',
    lettersInLanguage: ['f', 'o']
  },
  L2: {
    name: 'bar'
  },
  build: 'baz'
};

@Injectable({ providedIn: 'root' })
export class MtdService {
  _dictionary_data$ = new BehaviorSubject<DictionaryData[]>(
    // FIXME: should get `window` otherwise so we can mock it
    window['dataDict'] || []
  );
  _config$ = new BehaviorSubject<Config>(window['config'] || TESTCONFIG);
  remoteData$: any;
  remoteConfig$: any;
  base: string = environment.apiBaseURL;

  private shuffle(array) {
    let copy = array.map(x => x);
    let tmp,
      current,
      top = copy.length;
    if (top) {
      while (--top) {
        current = Math.floor(Math.random() * (top + 1));
        tmp = copy[current];
        copy[current] = copy[top];
        copy[top] = tmp;
      }
    }
    return copy;
  }

  getRandom$(no_random: number) {
    return this._dictionary_data$
      .asObservable()
      .pipe(map(x => this.shuffle(x).slice(0, no_random)));
  }

  getSlice$(start_index: number, no_slice: number) {
    return this._dictionary_data$
      .asObservable()
      .pipe(map(x => x.slice(start_index, start_index + no_slice)));
  }

  hasAudio(entry) {
    if (!('audio' in entry)) return false;
    if (entry.audio instanceof Array) {
      const files = entry.audio.filter(audioFile => audioFile.filename);
      return !!files.length;
    }
    return !!entry.audio;
  }

  get allAudioEntries$() {
    return this._dictionary_data$
      .asObservable()
      .pipe(map(arr => arr.filter(this.hasAudio)));
  }

  get config$() {
    return this._config$.asObservable();
  }

  get name$() {
    return this.config$.pipe(map(config => config.L1.name));
  }

  get dataDict$() {
    return this._dictionary_data$.asObservable().pipe(
      map(entries =>
        entries.sort(function(a, b) {
          return a['sorting_form'][0] - b['sorting_form'][0];
        })
      )
    );
  }

  get config_value() {
    return this._config$.value;
  }

  get dataDict_value() {
    return this._dictionary_data$.value;
  }

  get categories$(): Observable<object> {
    return this._dictionary_data$.asObservable().pipe(
      map(entries => {
        const keys = uniq(entries.map(x => x['source']));
        const categories: object = {};
        for (const key of keys) {
          categories[key] = entries.filter(x => x['source'] === key);
        }
        const semantic_categories = uniq(
          entries.map(entry => {
            if (
              entry.theme &&
              entry.theme !== undefined &&
              typeof entry.theme === 'string'
            ) {
              return entry.theme.toLowerCase();
            }
          })
        ).sort();

        for (const cat of semantic_categories) {
          if (cat) {
            categories[cat] = entries.filter(entry => entry.theme === cat);
          }
        }

        const audioEntries = entries.filter(this.hasAudio);
        if (
          audioEntries.length > 0 &&
          (audioEntries.length < entries.length * 0.75 || META.browseAudio)
        ) {
          categories['audio'] = {};
          categories['audio'] = audioEntries;
        }
        return categories;
      })
    );
  }

  get category_keys$() {
    return this.categories$.pipe(map(cats => Object.keys(cats)));
  }
}
