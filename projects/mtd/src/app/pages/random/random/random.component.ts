import { Component, ChangeDetectionStrategy } from '@angular/core';
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
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  constructor(private mtdService: MtdService) {}

  getRandom() {
    this.entries$ = this.mtdService.getRandom$(10);
  }
}
