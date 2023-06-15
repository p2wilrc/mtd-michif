import {
  Component,
  ChangeDetectorRef,
  ChangeDetectionStrategy
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { DictionaryData } from '../../../core/models';
import {
  MtdService,
  ROUTE_ANIMATIONS_ELEMENTS
} from '../../../core/core.module';
import { Observable } from 'rxjs';

@Component({
  selector: 'mtd-random',
  templateUrl: './random.component.html',
  styleUrls: ['./random.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class RandomComponent {
  displayNav = true;
  entries$: Observable<DictionaryData[]>;
  unsubscribe$ = new Subject<void>();
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  show?: string;
  constructor(
    private mtdService: MtdService,
    private route: ActivatedRoute,
    private ref: ChangeDetectorRef
  ) {
    this.route.queryParams
      .pipe(takeUntil(this.unsubscribe$))
      .subscribe(params => {
        this.show = params.show;
        this.ref.markForCheck();
      });
  }

  ngOnDestroy() {
    this.unsubscribe$.next();
  }

  getRandom() {
    this.entries$ = this.mtdService.getRandom$(10);
  }
}
