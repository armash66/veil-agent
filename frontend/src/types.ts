export type AppView = 'home' | 'chat';

export interface ProductItem {
  title: string;
  price: string;
  spec: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  products?: ProductItem[];
  cheapestProduct?: string;
}
