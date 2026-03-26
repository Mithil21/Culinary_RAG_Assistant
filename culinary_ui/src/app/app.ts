// Author: Mithil Baria
import { Component } from '@angular/core';
import { ChatComponent } from './chat/chat.component';
import { provideHttpClient } from '@angular/common/http';

@Component({
  selector: 'app-root',
  imports: [ChatComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {}
