// Author: Mithil Baria
import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, Message } from '../chat.service';
import { RecipeFormatterPipe } from './recipe-formatter.pipe';
import { MarkdownToHtmlPipe } from './markdown-to-html.pipe';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, RecipeFormatterPipe, MarkdownToHtmlPipe],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent {
  messages = signal<Message[]>([]);
  userInput = signal('');
  isLoading = signal(false);
  isDark = signal(false);
  sidebarOpen = signal(true);
  chats = signal<{ id: number; label: string; messages: Message[] }[]>([]);
  currentChatId = signal<number | null>(null);
  chatCounter = 0;

  constructor(private chatService: ChatService) {
    this.startNewChat();
  }

  toggleTheme() {
    this.isDark.update(dark => !dark);
  }

  toggleSidebar() {
    this.sidebarOpen.update(open => !open);
  }

  startNewChat() {
    this.chatCounter++;
    const newChat = {
      id: this.chatCounter,
      label: `Chat ${this.chatCounter}`,
      messages: [
        { 
          role: 'assistant' as const, 
          content: 'Hi! I am your South Asian Culinary Assistant. What would you like to cook today?' 
        }
      ]
    };
    
    this.chats.update(chats => [...chats, newChat]);
    this.currentChatId.set(newChat.id);
    this.messages.set(newChat.messages);
    this.userInput.set('');
    this.isLoading.set(false);
  }

  switchChat(chatId: number) {
    const chat = this.chats().find(c => c.id === chatId);
    if (chat) {
      this.currentChatId.set(chatId);
      this.messages.set(chat.messages);
    }
  }

  saveCurrentChat() {
    const chatId = this.currentChatId();
    if (chatId) {
      this.chats.update(chats => 
        chats.map(c => c.id === chatId ? { ...c, messages: this.messages() } : c)
      );
    }
  }

  // sendMessage() {
  //   const input = this.userInput().trim();
  //   if (!input || this.isLoading()) return;

  //   this.messages.update(msgs => [...msgs, { role: 'user', content: input }]);
  //   this.userInput.set('');
  //   this.isLoading.set(true);

  //   this.chatService.sendMessage(input).subscribe({
  //     next: (response) => {
  //       this.messages.update(msgs => [...msgs, { 
  //         role: 'assistant', 
  //         content: response.answer || response.message || 'No response',
  //         chunks: response.chunks_used || [],
  //         intent: response.intent
  //       }]);
  //       this.isLoading.set(false);
  //     },
  //     error: () => {
  //       this.messages.update(msgs => [...msgs, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
  //       this.isLoading.set(false);
  //     }
  //   });
  // }

  sendMessage() {
    const input = this.userInput().trim();
    if (!input || this.isLoading()) return;

    this.messages.update(msgs => [...msgs, { role: 'user', content: input }]);
    this.userInput.set('');
    this.isLoading.set(true);

    this.chatService.sendMessage(this.messages()).subscribe({
      next: (response) => {
        this.messages.update(msgs => [...msgs, { 
          role: 'assistant', 
          content: response.answer || response.message || 'No response',
          chunks: response.chunks || [],
          intent: response.intent
        }]);
        this.saveCurrentChat();
        this.isLoading.set(false);
      },
      error: () => {
        this.messages.update(msgs => [...msgs, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
        this.saveCurrentChat();
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
