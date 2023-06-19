import {
  Component,
  Inject,
  OnInit,
  ChangeDetectionStrategy
} from '@angular/core';
import {
  MatDialog,
  MatDialogRef,
  MAT_DIALOG_DATA
} from '@angular/material/dialog';

@Component({
  selector: 'mtd-report-dialog',
  templateUrl: './report-dialog.component.html',
  styleUrls: ['./report-dialog.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ReportDialogComponent implements OnInit {
  constructor(
    public dialogRef: MatDialogRef<ReportDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data
  ) {}

  ngOnInit(): void {}

  /*
  async openReport() {
    if (!(this.data && this.data.entry)) return;
    if (this.reported) return;
    const entry_id = encodeURIComponent(this.data.entry.entryID);
    const url = encodeURIComponent(window.location.href);
    const word = encodeURIComponent(
      `${this.data.entry.word}: ${this.data.entry.definition}`
    );
    const reporter = `https://dictionary.michif.org/report.php?id=${entry_id}&url=${url}&word=${word}`;
    console.log(reporter);
    const response = await fetch(reporter);
    if (response.ok) this.reported = true;
    this.ref.markForCheck();
  }
*/

  send(): void {
    this.dialogRef.close('reported');
  }
}
