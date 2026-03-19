import { defineCollection, z } from "astro:content";

const daily = defineCollection({
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    source: z.string(),
  }),
});

export const collections = { daily };
