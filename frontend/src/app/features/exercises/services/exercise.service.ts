import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class ExerciseService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000/api/v1/exercises/check';

  checkTranslation(translation: string, task: string): Observable<any> {
    return this.http.post(this.apiUrl, {
      student_translation: translation,
      original_task: task,
      context_table: '',
      context_journal: '',
    });
  }
}
