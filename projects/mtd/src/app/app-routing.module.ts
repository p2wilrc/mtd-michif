import { NgModule } from '@angular/core';
import { Routes, RouterModule, PreloadAllModules } from '@angular/router';

const routes: Routes = [
  {
    path: '',
    redirectTo: 'dev/construction',
    pathMatch: 'full'
  },
  {
    path: 'dev/construction',
    loadChildren: () =>
      import('./pages/construction/construction.module').then(
        m => m.ConstructionModule
      )
  },
  {
    path: 'dev/home',
    loadChildren: () =>
      import('./pages/home/home.module').then(m => m.HomeModule)
  },
  {
    path: 'dev/about',
    loadChildren: () =>
      import('./pages/about/about.module').then(m => m.AboutModule)
  },
  {
    path: 'dev/browse',
    loadChildren: () =>
      import('./pages/browse/browse.module').then(m => m.BrowseModule)
  },
  {
    path: 'dev/bookmarks',
    loadChildren: () =>
      import('./pages/bookmarks/bookmarks.module').then(m => m.BookmarksModule)
  },
  {
    path: 'dev/random',
    loadChildren: () =>
      import('./pages/random/random.module').then(m => m.RandomModule)
  },
  {
    path: 'dev/search',
    loadChildren: () =>
      import('./pages/search/search.module').then(m => m.SearchModule)
  },
  {
    path: 'dev/settings',
    loadChildren: () =>
      import('./pages/settings/settings.module').then(m => m.SettingsModule)
  }
  //{
  //  path: '**',
  //  redirectTo: 'home'
  //}
];

@NgModule({
  // useHash supports github.io demo page, remove in your app
  imports: [
    RouterModule.forRoot(routes, {
      scrollPositionRestoration: 'enabled',
      preloadingStrategy: PreloadAllModules
    })
  ],
  exports: [RouterModule]
})
export class AppRoutingModule {}
