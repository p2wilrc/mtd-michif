import { Component, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'mtd-introduction',
  templateUrl: './introduction.component.html',
  styleUrls: [
    '../../shared/static/static.component.scss',
    './introduction.component.scss'
  ],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class IntroductionComponent {}
