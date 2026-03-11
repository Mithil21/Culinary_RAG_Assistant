import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

@Pipe({
  name: 'markdownToHtml',
  standalone: true
})
export class MarkdownToHtmlPipe implements PipeTransform {
  constructor(private sanitizer: DomSanitizer) {}

  transform(text: string): SafeHtml {
    let html = text
      .replace(/### (.+)/g, '<h3>$1</h3>')
      .replace(/## (.+)/g, '<h2>$1</h2>')
      .replace(/# (.+)/g, '<h1>$1</h1>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/^- (.+)/gm, '<li>$1</li>')
      .replace(/^\d+\. (.+)/gm, '<li>$1</li>')
      .replace(/---/g, '<hr>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
    
    html = html.replace(/(<li>.*<\/li>)/s, (match) => {
      if (match.includes('<br>')) {
        return match.replace(/<br>/g, '');
      }
      return match;
    });
    
    html = html.replace(/(<li>[^<]*<\/li>\s*)+/g, (match) => {
      return '<ul>' + match + '</ul>';
    });
    
    html = '<p>' + html + '</p>';
    html = html.replace(/<p><\/p>/g, '').replace(/<p>\s*<(h[1-3]|ul|hr)/g, '<$1').replace(/<\/(h[1-3]|ul|hr)>\s*<\/p>/g, '</$1>');
    
    return this.sanitizer.sanitize(1, html) || '';
  }
}
