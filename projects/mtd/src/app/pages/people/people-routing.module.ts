import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import { PeopleComponent } from './people.component';

const routes: Routes = [
  {
    path: '',
    component: PeopleComponent,
    data: { title: 'mtd.menu.people' }
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class PeopleRoutingModule {}
