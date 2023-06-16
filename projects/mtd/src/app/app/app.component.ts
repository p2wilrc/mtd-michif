import browser from 'browser-detect';
import { Component, OnInit, OnDestroy } from '@angular/core';
import { Store, select } from '@ngrx/store';
import { Observable, Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { marker } from '@biesbjerg/ngx-translate-extract-marker';

import { environment as env } from '../../environments/environment';
import { META } from '../../config/config';

import {
  routeAnimations,
  LocalStorageService,
  selectSettingsStickyHeader,
  selectSettingsLanguage,
  selectEffectiveTheme
} from '../core/core.module';
import {
  actionSettingsChangeAnimationsPageDisabled,
  actionSettingsChangeLanguage
} from '../core/settings/settings.actions';

@Component({
  selector: 'mtd-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  animations: [routeAnimations]
})
export class AppComponent implements OnInit, OnDestroy {
  displayNav = false;
  isProd = env.production;
  envName = env.envName;
  version = env.versions.app;
  year = new Date().getFullYear();
  logo = 'assets/icon-512x512.png';
  languages = META.languages;
  Meta = META;
  navigation = [
    { link: 'search', label: marker('mtd.menu.search') },
    { link: 'browse', label: marker('mtd.menu.browse') },
    { link: 'random', label: marker('mtd.menu.random') },
    { link: 'bookmarks', label: marker('mtd.menu.bookmarks') },
    { link: 'about', label: marker('mtd.menu.about') }
  ];
  navigationSideMenu = [
    ...this.navigation,
    { link: 'settings', label: 'mtd.menu.settings' }
  ];

  stickyHeader$: Observable<boolean>;
  language$: Observable<string>;
  theme$: Observable<string>;
  unsubscribe$ = new Subject<void>();
  constructor(
    private store: Store,
    private storageService: LocalStorageService
  ) {}

  private static isIEorEdgeOrSafari() {
    return ['ie', 'edge', 'safari'].includes(browser().name);
  }

  ngOnDestroy(): void {
    this.unsubscribe$.next();
  }

  ngOnInit(): void {
    this.storageService.testLocalStorage();
    if (AppComponent.isIEorEdgeOrSafari()) {
      this.store.dispatch(
        actionSettingsChangeAnimationsPageDisabled({
          pageAnimationsDisabled: true
        })
      );
    }
    this.stickyHeader$ = this.store.pipe(select(selectSettingsStickyHeader));
    this.language$ = this.store.pipe(select(selectSettingsLanguage));
    this.theme$ = this.store.pipe(select(selectEffectiveTheme));
  }

  onLanguageSelect({ value: language }) {
    this.store.dispatch(actionSettingsChangeLanguage({ language }));
  }
}
