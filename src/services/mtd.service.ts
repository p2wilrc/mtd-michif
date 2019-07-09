import { Injectable } from "@angular/core";
import { BehaviorSubject, Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Config, DictionaryData } from '../app/models'
import { HttpClient, HttpResponse } from "@angular/common/http";
import { slugify } from '../app/global'
import { uniq } from 'lodash';
import { environment } from '../environments/environment'
// import { AlertController } from '@ionic/angular';

@Injectable({ providedIn: 'root' })
export class MTDService {
    _dictionary_data$ = new BehaviorSubject<DictionaryData[]>(window['dataDict'])
    _config$ = new BehaviorSubject<Config>(window['config'])
    slug: string;
    remote_data$: any;
    remote_config$: any;
    base: string = environment.apiBaseURL;
    // remote: string = environment.remoteSlug;
    constructor(private http: HttpClient) {

        console.log(this.base)
        this.slug = slugify(this._config$.getValue().L1.name);
        // this.slug = this.remote
        // console.log(this.slug)
        this.remote_data$ = this.http.get(`https://mtd-fv.herokuapp.com/api/v1/languages?name=${this.slug}&only-data=true`, { observe: 'response' });
        this.remote_config$ = this.http.get(`https://mtd-fv.herokuapp.com/api/v1/languages?name=${this.slug}&only-config=true`, { observe: 'response' });
        // TODO: if in storage
        if (false) {
            // TODO: check remote build is newer
            this.remote_config$.subscribe(x => {
                if (x.status === 200) { // TODO: and storage.config.build < x.build
                    this._config$.next(x.body)
                    this.remote_data$.subscribe(x => {
                        if (x.status === 200) {
                            this.presentUpdateAlert()
                            // setTimeout(() => {
                            this._dictionary_data$.next(x.body)
                            // }, 3000)
                        } else {
                            this.presentUpdateFailedAlert()
                            // TODO: return error message
                        }
                    })
                } else {
                    this.presentUpdateFailedAlert()
                    // TODO: return error message
                }
            })
        } else {
            // TODO: try and update from remote
            this.remote_config$.subscribe(x => {
                if (x.status === 200) {
                    this._config$.next(x.body)
                    this.remote_data$.subscribe(x => {
                        if (x.status === 200) {
                            this._dictionary_data$.next(x.body)
                        } else {
                            // return error message
                        }
                    })
                } else {
                    // return error message
                }
            })
        }



    }

    async presentUpdateAlert() {
        console.log('alert')
        // const alert = await this.alertCtrl.create({
        //     header: 'Success',
        //     message: 'New words have been updated from the server.',
        //     buttons: ['OK']
        // });
        // await alert.present();
    }

    async presentUpdateFailedAlert() {
        console.log('alert')
        // const alert = await this.alertCtrl.create({
        //     header: 'Oops',
        //     message: "There might be new words, but we couldn't check. Try connecting to the internet.",
        //     buttons: ['OK']
        // });
        // await alert.present();
    }

    private shuffle(array) {
        var tmp, current, top = array.length;
        if (top)
            while (--top) {
                current = Math.floor(Math.random() * (top + 1));
                tmp = array[current];
                array[current] = array[top];
                array[top] = tmp;
            }
        return array;
    }

    getRandom$(no_random: number) {
        return this._dictionary_data$.asObservable().pipe(
            map((x) => this.shuffle(x).slice(0, no_random))
        )
    }

    getSlice$(start_index: number, no_slice: number) {
        return this._dictionary_data$.asObservable().pipe(
            map((x) => x.slice(start_index, start_index + no_slice))
        )
    }

    get allAudioEntries$() {
        return this._dictionary_data$.asObservable().pipe(
            map((arr) => arr.filter((x) => x.audio))
        )
    }

    get config$() {
        return this._config$.asObservable()
    }

    get name$() {
        return this.config$.pipe(
            map((config) => config.L1.name)
        )
    }

    get dataDict$() {
        return this._dictionary_data$.asObservable().pipe(
            map(entries => entries.sort(function (a, b) { return a['sorting_form'][0] - b['sorting_form'][0] }))
        )
    }

    get config_value() {
        return this._config$.getValue()
    }

    get dataDict_value() {
        return this._dictionary_data$.getValue()
    }

    get categories$(): Observable<object> {
        return this._dictionary_data$.asObservable().pipe(
            map((entries) => {
                let keys = uniq(entries.map(x => x['source']));
                let categories: object = {};
                for (let key of keys) {
                    categories[key] = entries.filter((x) => x['source'] == key)
                }
                let semantic_categories = uniq(entries.map((entry) => {
                    if (entry.theme && entry.theme !== undefined && typeof entry.theme === 'string') {
                        return entry.theme.toLowerCase()
                    }
                })).sort()

                for (let cat of semantic_categories) {
                    if (cat) {
                        categories[cat] = entries.filter((entry) => entry.theme === cat)
                    }
                }

                let audioEntries = entries.filter((x) => x.audio)

                if (audioEntries.length > 0 && audioEntries.length < (entries.length * .5)) {
                    categories["audio"] = {};
                    categories["audio"] = audioEntries;
                }
                return categories
            })
        )
    }

    get category_keys$() {
        return this.categories$.pipe(
            map((cats) => Object.keys(cats))
        )
    }


}