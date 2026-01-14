import { Component, signal, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { firstValueFrom } from 'rxjs';
import { ExerciseService } from '../services/exercise.service';

interface ChatMessage {
  role: 'teacher' | 'student';
  text: string;
  isEvaluation?: boolean;
  evaluationData?: any;
}

@Component({
  selector: 'app-exercise-view',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatInputModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatDividerModule,
  ],
  templateUrl: './exercise-view.component.html',
  styleUrls: ['./exercise-view.component.scss'],
})
export class ExerciseViewComponent implements OnInit {
  messages = signal<ChatMessage[]>([]);

  userInput = signal<string>('');
  isBusy = signal<boolean>(false);
  private exerciseService = inject(ExerciseService);

  ngOnInit() {
    this.loadNewTask();
  }

  async loadNewTask() {
    this.isBusy.set(true);
    this.messages.update((msgs) => [
      ...msgs,
      { role: 'teacher', text: 'Анализирую твою успеваемость и подбираю задание...' },
    ]);

    try {
      const response = await firstValueFrom(this.exerciseService.getNextTask());

      this.messages.update((msgs) => {
        const newMsgs = msgs.slice(0, -1);
        return [...newMsgs, { role: 'teacher', text: response.task_text }];
      });
    } catch (error) {
      console.error('Error fetching task', error);
      this.messages.update((msgs) => [
        ...msgs,
        { role: 'teacher', text: 'Не удалось загрузить задание. Проверь сервер.' },
      ]);
    } finally {
      this.isBusy.set(false);
    }
  }

  async sendAnswer() {
    const text = this.userInput().trim();
    if (!text || this.isBusy()) return;

    const lastTeacherMsg = [...this.messages()]
      .reverse()
      .find((m) => m.role === 'teacher' && !m.isEvaluation);

    const taskText = lastTeacherMsg ? lastTeacherMsg.text : '';

    this.updateChat('student', text);
    this.userInput.set('');
    this.isBusy.set(true);

    try {
      const response = await firstValueFrom(this.exerciseService.checkTranslation(text, taskText));
      const aiData = response.result;

      this.messages.update((msgs) => [
        ...msgs,
        {
          role: 'teacher',
          text: '',
          isEvaluation: true,
          evaluationData: aiData,
        },
      ]);

      await this.loadNewTask();
    } catch (error) {
    } finally {
      this.isBusy.set(false);
    }
  }

  private updateChat(role: 'teacher' | 'student', text: string) {
    this.messages.update((msgs) => [...msgs, { role, text }]);
  }

  onKeyDown(event: KeyboardEvent) {
    if (event.ctrlKey && event.key === 'Enter') {
      this.sendAnswer();
    }
  }
}
