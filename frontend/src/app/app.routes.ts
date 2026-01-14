import { Routes } from '@angular/router';
import { ExerciseViewComponent } from './features/exercises/exercise-view/exercise-view.component';

export const routes: Routes = [
  // Когда путь пустой (главная страница), показываем наш чат
  { path: '', component: ExerciseViewComponent },
];
