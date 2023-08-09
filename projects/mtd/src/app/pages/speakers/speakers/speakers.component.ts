import { Router, ActivatedRoute, ParamMap } from '@angular/router';
import {
  Component,
  ChangeDetectorRef,
  OnInit,
  ChangeDetectionStrategy
} from '@angular/core';
import { ROUTE_ANIMATIONS_ELEMENTS } from '../../../core/core.module';

@Component({
  selector: 'mtd-speakers',
  templateUrl: './speakers.component.html',
  styleUrls: ['./speakers.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SpeakersComponent implements OnInit {
  routeAnimationsElements = ROUTE_ANIMATIONS_ELEMENTS;
  speaker = 'verna';
  fullname = {
    verna: 'Verna DeMontigny',
    sandra: 'Sandra Houle',
    albert: 'Albert Parisien Sr.'
  };
  photos = {
    verna: 'assets/Verna_DeMontigny.jpg',
    sandra: 'assets/Sandra_Houle.jpg',
    albert: 'assets/Albert_Parisien.jpg'
  };
  constructor(private route: ActivatedRoute, private ref: ChangeDetectorRef) {}

  ngOnInit() {
    this.route.paramMap.subscribe(paramMap => {
      const speaker = paramMap.get('speaker');
      if (speaker !== null) {
        console.log(`wtf ${speaker}`);
        this.speaker = speaker;
        this.ref.markForCheck();
      }
    });
  }
}
