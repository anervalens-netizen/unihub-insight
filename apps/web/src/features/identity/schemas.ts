import { z } from 'zod';

export const capabilities = [
  'insight:analytics',
  'insight:management',
  'insight:hr',
  'insight:pnl',
  'insight:admin',
] as const;

export type Capability = (typeof capabilities)[number];

export const userSchema = z.object({
  subject: z.string(),
  email: z.string().nullable().optional(),
  name: z.string().nullable().optional(),
  groups: z.array(z.string()),
  capabilities: z.array(z.enum(capabilities)),
  is_demo: z.boolean(),
});

export type UserContext = z.infer<typeof userSchema>;
