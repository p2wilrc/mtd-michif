import { Component, ChangeDetectionStrategy } from '@angular/core';
import { ROUTE_ANIMATIONS_ELEMENTS } from '../../core/core.module';

@Component({
  selector: 'mtd-static',
  styleUrls: ['./static.component.scss'],
  templateUrl: './static.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class StaticComponent {
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
}
