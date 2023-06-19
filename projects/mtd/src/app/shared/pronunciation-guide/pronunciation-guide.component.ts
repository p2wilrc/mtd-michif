import { Component, OnInit, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'mtd-pronunciation-guide',
  templateUrl: './pronunciation-guide.component.html',
  styleUrls: ['./pronunciation-guide.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PronunciationGuideComponent implements OnInit {
  constructor() {}

  ngOnInit(): void {}
}
