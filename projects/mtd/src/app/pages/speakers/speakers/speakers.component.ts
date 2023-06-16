import { Component, ChangeDetectionStrategy } from '@angular/core';
import { META } from '../../../../config/config';
import { ROUTE_ANIMATIONS_ELEMENTS } from '../../../core/core.module';

export interface Contributor {
  text: string;
  img: string | false;
  name: string;
  title: string;
}

@Component({
  selector: 'mtd-speakers',
  templateUrl: './speakers.component.html',
  styleUrls: ['./speakers.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SpeakersComponent {
  displayNav = true;
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  contributors = META.contributors;
  verna = 'assets/Verna_DeMontigny.jpg';
  sandra = 'assets/Sandra_Houle.jpg';
  albert = 'assets/Albert_Parisien.jpg';
}
