import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConstructionComponent } from './construction/construction.component';
//import { SharedModule } from '../../shared/shared.module';
import { ConstructionRoutingModule } from './construction-routing.module';

@NgModule({
  declarations: [ConstructionComponent],
  imports: [CommonModule, ConstructionRoutingModule]
})
export class ConstructionModule {}
