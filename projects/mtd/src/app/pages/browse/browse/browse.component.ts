import { Component, OnDestroy, ChangeDetectionStrategy } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { DictionaryData } from '../../../core/models';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { map, tap, takeUntil } from 'rxjs/operators';
import { META } from '../../../../config/config';
import {
  BookmarksService,
  MtdService,
  ROUTE_ANIMATIONS_ELEMENTS
} from '../../../core/core.module';
@Component({
  selector: 'mtd-browse',
  templateUrl: './browse.component.html',
  styleUrls: ['./browse.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BrowseComponent implements OnDestroy {
  currentEntries$: BehaviorSubject<DictionaryData[]>;
  currentX: DictionaryData[];
  displayCategories$: Observable<any>;
  displayLetters$: Observable<any>;
  letters: string[];
  initialLetters: string[];
  selectedCategory = 'words';
  selectedLetter: number;
  startIndex$: BehaviorSubject<number> = new BehaviorSubject(0);
  default_shown = 8;
  // currentBrowsingLetter: String = this.letters[this.currentBrowsingEntries[0].sorting_form[0]];
  letterSelectOptions: Object = { header: 'Select a Letter' };
  categorySelectOptions: Object = { header: 'Select a Category' };
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  unsubscribe$ = new Subject<void>();
  constructor(
    public bookmarkService: BookmarksService,
    private mtdService: MtdService,
    private route: ActivatedRoute,
    private router: Router
  ) {
    this.displayCategories$ = this.mtdService.category_keys$;
    this.currentEntries$ = new BehaviorSubject<DictionaryData[]>(
      this.mtdService.dataDict_value
    );
    this.route.params.subscribe(params => {
      const start = parseInt(params.start ?? 0);
      const clamped = Math.max(
        0,
        Math.min(start, this.currentEntries$.getValue().length - 1)
      );
      if (start !== clamped)
        this.router.navigate([clamped], { relativeTo: this.route.parent });
      else this.startIndex$.next(clamped);
    });
    this.route.queryParams.subscribe(params => {
      if ('default_shown' in params)
        this.default_shown = parseInt(params.default_shown);
    });
    this.mtdService.dataDict$
      .pipe(takeUntil(this.unsubscribe$))
      .subscribe(x => {
        this.currentEntries$.next(x);
        this.initializeEntries();
      });
    this.currentEntries$
      .pipe(
        map(entries => this.getXFrom(this.startIndex$.value, entries)),
        takeUntil(this.unsubscribe$)
      )
      .subscribe(entries => (this.currentX = entries));
    this.startIndex$
      .pipe(
        map(i => this.getXFrom(i, this.currentEntries$.getValue())),
        takeUntil(this.unsubscribe$)
      )
      .subscribe(entries => (this.currentX = entries));
    this.initializeEntries();
  }

  ngOnDestroy(): void {
    this.unsubscribe$.next();
  }

  getXFrom(
    i: number,
    entries: DictionaryData[],
    x: number = this.default_shown
  ): DictionaryData[] {
    return entries.slice(i, i + x);
  }

  initializeEntries() {
    // Add letter index to first words of that letter in entries
    this.letterInit();
  }

  letterNeverStarts(letter) {
    return this.displayLetters$.pipe(
      map(letters => letters.indexOf(letter) === -1)
    );
  }

  highlightLetter(letter) {
    return this.letters.indexOf(letter) === this.currentX[0].sorting_form[0];
  }

  // Determine whether letter occurs word-initially
  letterInit() {
    this.letters = this.mtdService.config_value.L1.lettersInLanguage;
    this.displayLetters$ = this.currentEntries$.pipe(
      map(entries => {
        const newLetters = [];
        for (const letter of this.letters) {
          const ind = this.letters.indexOf(letter);
          for (const entry of entries) {
            if (entry.sorting_form[0] === ind) {
              entry.firstWordIndex = ind;
              newLetters.push(letter);
              break;
            }
          }
        }
        return newLetters;
      })
    );
  }
  // Scroll to previous X entries
  prevX() {
    let current_val = this.startIndex$.value;
    if (current_val - this.default_shown > 0) {
      this.router.navigate([(current_val -= this.default_shown)], {
        relativeTo: this.route.parent
      });
    } else {
      this.router.navigate([0], { relativeTo: this.route.parent });
    }
  }

  // Scroll to next X entries
  nextX() {
    let current_val = this.startIndex$.value;
    if (
      current_val + this.default_shown <
      this.currentEntries$.getValue().length
    ) {
      this.router.navigate([current_val + this.default_shown], {
        relativeTo: this.route.parent
      });
    } else {
      this.router.navigate(
        [
          Math.max(
            this.currentEntries$.getValue().length - this.default_shown,
            0
          )
        ],
        { relativeTo: this.route.parent }
      );
    }
  }

  // Scroll to letter
  scrollTo(letter: string) {
    const letterIndex = this.letters.indexOf(letter);
    for (const entry of this.currentEntries$.getValue()) {
      if (entry.sorting_form[0] === letterIndex) {
        this.router.navigate([this.currentEntries$.getValue().indexOf(entry)], {
          relativeTo: this.route.parent
        });
        break;
      }
    }
  }

  selectCategory(category: string) {
    if (category === 'words') {
      this.mtdService.dataDict$
        .pipe(map(x => this.currentEntries$.next(x)))
        .subscribe()
        .unsubscribe();
    } else {
      this.mtdService.categories$
        .pipe(map(x => this.currentEntries$.next(x[category])))
        .subscribe()
        .unsubscribe();
    }
    this.selectedCategory = category;
    this.startIndex$.next(0);
    this.letterInit();
  }
}
