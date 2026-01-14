import { Component, signal, inject } from '@angular/core';
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
export class ExerciseViewComponent {
  // Сигналы для управления состоянием
  messages = signal<ChatMessage[]>([
    {
      role: 'teacher',
      text: 'Привет! Давай потренируемся. Переведи следующее предложение:\n\n"Кошка спит на мягком диване."',
    },
  ]);

  userInput = signal<string>('');
  isBusy = signal<boolean>(false);
  private exerciseService = inject(ExerciseService);

  // Метод отправки ответа
  async sendAnswer() {
    const text = this.userInput().trim();
    if (!text || this.isBusy()) return;

    // Находим последнее сообщение учителя, чтобы понять, какое было задание
    // (В реальном приложении ID задания хранят отдельно, но для чата пойдет)
    const lastTeacherMsg = [...this.messages()]
      .reverse()
      .find((m) => m.role === 'teacher' && !m.isEvaluation);
    const taskText = lastTeacherMsg ? lastTeacherMsg.text : 'Translate this...';

    this.updateChat('student', text);
    this.userInput.set('');
    this.isBusy.set(true);

    try {
      // РЕАЛЬНЫЙ ВЫЗОВ НА БЕКЕНД
      // Используем firstValueFrom для превращения Observable в Promise (удобнее с async/await)
      const response = await firstValueFrom(this.exerciseService.checkTranslation(text, taskText));

      // response.result - это тот самый JSON от Gemini
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

      this.updateChat('teacher', 'Следующее задание (пока заглушка)...');
    } catch (error) {
      console.error('Ошибка сервера:', error);
      this.updateChat('teacher', 'Ошибка связи с сервером AI. Попробуй позже.');
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
