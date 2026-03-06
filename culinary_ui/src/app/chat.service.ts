import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  chunks?: string[]; // Optional: To store the recipe source chunks!
  intent?: string;   // Optional: To show if it was A, B, or C
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  // 1. Changed port to 8000
  private apiUrl = 'http://localhost:8000/api/ask/';

  constructor(private http: HttpClient) {}

  sendMessage(userMessage: string): Observable<any> {
    // 2. Mapped the variable to the "prompt" key Django expects
    return this.http.post(this.apiUrl, { prompt: userMessage });
  }
}