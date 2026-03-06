import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, Message } from '../chat.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent {
  messages = signal<Message[]>([]);
  userInput = signal('');
  isLoading = signal(false);

  constructor(private chatService: ChatService) {}

  sendMessage() {
    const input = this.userInput().trim();
    if (!input || this.isLoading()) return;

    this.messages.update(msgs => [...msgs, { role: 'user', content: input }]);
    this.userInput.set('');
    this.isLoading.set(true);

    this.chatService.sendMessage(input).subscribe({
      next: (response) => {
        this.messages.update(msgs => [...msgs, { 
          role: 'assistant', 
          content: response.answer || response.message || 'No response',
          chunks: response.chunks_used || [],
          intent: response.intent
        }]);
        this.isLoading.set(false);
      },
      error: () => {
        this.messages.update(msgs => [...msgs, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
        this.isLoading.set(false);
      }
    });
  }

  handleKeyPress(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
}
