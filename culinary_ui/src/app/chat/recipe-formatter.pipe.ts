// Author: Mithil Baria
import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'recipeFormatter',
  standalone: true
})
export class RecipeFormatterPipe implements PipeTransform {
  transform(content: string): { type: 'recipe' | 'text', data: any } {
    if (content.includes('Ingredients:') && content.includes('Instructions:')) {
      return { type: 'recipe', data: this.parseRecipe(content) };
    }
    return { type: 'text', data: content };
  }

  private parseRecipe(content: string) {
    const lines = content.split('\n').map(l => l.trim()).filter(l => l);
    const recipe: any = { title: '', intro: '', about: '', ingredients: [], instructions: [] };
    let section = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      if (i === 0 && !line.startsWith('**Ingredients:**') && !line.startsWith('Ingredients:')) {
        recipe.title = line;
        section = 'title';
      } else if (line.startsWith('**Ingredients:**') || line === 'Ingredients:') {
        section = 'ingredients';
      } else if (line.startsWith('**Instructions:**') || line === 'Instructions:') {
        section = 'instructions';
      } else if (line.startsWith('-') && section === 'ingredients') {
        recipe.ingredients.push(line.substring(1).trim());
      } else if (/^\d+\./.test(line) && section === 'instructions') {
        recipe.instructions.push({ text: line.replace(/^\d+\.\s*/, '') });
      }
    }

    return recipe;
  }
}
