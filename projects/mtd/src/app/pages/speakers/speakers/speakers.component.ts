import { Component, ChangeDetectionStrategy } from '@angular/core';
import { ROUTE_ANIMATIONS_ELEMENTS } from '../../../core/core.module';

@Component({
  selector: 'mtd-speakers',
  templateUrl: './speakers.component.html',
  styleUrls: ['./speakers.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SpeakersComponent {
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  verna = 'assets/Verna_DeMontigny.jpg';
  sandra = 'assets/Sandra_Houle.jpg';
  albert = 'assets/Albert_Parisien.jpg';
}
