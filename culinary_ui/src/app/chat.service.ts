import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  chunks?: string[]; 
  intent?: string;   
  selected_dishes?: string[];
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private apiUrl = 'http://localhost:8000/api/ask/';

  constructor(private http: HttpClient) {}

  // We now accept the full array of messages
  sendMessage(chatHistory: Message[]): Observable<any> {
    return this.http.post(this.apiUrl, { messages: chatHistory });
  }
}