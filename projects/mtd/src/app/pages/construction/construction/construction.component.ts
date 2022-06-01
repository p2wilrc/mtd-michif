import { Component, OnInit, ChangeDetectionStrategy } from '@angular/core';
import {
  MtdService,
  ROUTE_ANIMATIONS_ELEMENTS
} from '../../../core/core.module';

@Component({
  selector: 'mtd-home',
  templateUrl: './construction.component.html',
  styleUrls: [
    './construction.component.scss',
    '../../about/about/about.component.scss',
    '../../../../app/app/app.component.scss'
  ],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ConstructionComponent implements OnInit {
  displayNav = false;
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  construction = 'assets/construction.png';
  constructor(public mtdService: MtdService) {}

  ngOnInit(): void {}
}
