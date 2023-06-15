import {
  Component,
  Input,
  Inject,
  OnChanges,
  SimpleChange
} from '@angular/core';
import { WordModalComponent } from '../word-modal/word-modal.component';
import { DictionaryData } from '../../core/models';
import { BookmarksService, MtdService } from '../../core/core.module';

import {
  MatDialog,
  MatDialogRef,
  MAT_DIALOG_DATA
} from '@angular/material/dialog';

import { FileNotFoundDialogComponent } from '../file-not-found/file-not-found.component';
import { slugify } from 'transliteration';

const levenstein = function(string1, string2) {
  const a = string1,
    b = string2 + '',
    m = [],
    min = Math.min;
  let i, j;

  if (!(a && b)) return (b || a).length;

  for (i = 0; i <= b.length; m[i] = [i++]);
  for (j = 0; j <= a.length; m[0][j] = j++);

  for (i = 1; i <= b.length; i++) {
    for (j = 1; j <= a.length; j++) {
      m[i][j] =
        b.charAt(i - 1) === a.charAt(j - 1)
          ? m[i - 1][j - 1]
          : (m[i][j] = min(
              m[i - 1][j - 1] + 1,
              min(m[i][j - 1] + 1, m[i - 1][j] + 1)
            ));
    }
  }

  return m[b.length][a.length];
};

@Component({
  selector: 'mtd-entry-list',
  templateUrl: 'entry-list.component.html',
  styleUrls: ['entry-list.component.scss']
})
export class EntryListComponent implements OnChanges {
  pageName: string;
  edit = false;

  @Input() parentEdit: boolean;
  @Input() entries: DictionaryData[];
  @Input() searchTerm: string;
  @Input() threshold: number;
  @Input() shouldHighlight = false;
  @Input() searchResults: boolean = false;
  constructor(
    private bookmarkService: BookmarksService,
    public dialog: MatDialog,
    private mtdService: MtdService
  ) {
    // this.pageName = modalCtrl.name
  }

  async showModal(entry) {
    this.dialog.open(WordModalComponent, {
      data: { entry }
    });
  }

  playDefaultAudio(entry) {
    let audioPrefix = '';
    if ('audio_path' in this.mtdService.config_value) {
      audioPrefix = this.mtdService.config_value.audio_path;
    }
    const defaultAudio =
      audioPrefix +
      entry.audio.filter(audioFile => audioFile.filename)[0].filename;
    const audio = new Audio(defaultAudio);
    audio.onerror = () => this.fileNotFound(defaultAudio);
    audio.play();
  }

  fileNotFound(path) {
    const dialogRef = this.dialog.open(FileNotFoundDialogComponent, {
      width: '250px',
      data: { path }
    });
  }

  hasAudio(entry) {
    return this.mtdService.hasAudio(entry);
  }

  highlight(entry, langType) {
    let text;
    if (langType === 'L1') {
      text = entry.word;
    } else if (langType === 'L2') {
      text = entry.definition;
    }
    if (!this.searchTerm) {
      return text;
    }
    return text.replace(
      new RegExp(this.searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
      '<span class="langMatched">$&</span>'
    );
  }

  toggleBookmark(entry) {
    this.bookmarkService.toggleBookmark(entry);
  }

  ngOnChanges() {
    this.edit = this.parentEdit;
  }
}
