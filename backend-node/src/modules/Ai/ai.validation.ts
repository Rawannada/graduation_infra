import { z } from "zod";

export const summarizeSchema = {
  params: z.strictObject({
  fileId: z.string().min(1, "fileId is required"),
})
}


// export const chatSchema = z.object({
//   body: z.strictObject({
//     fileId: z.string().min(1, "fileId is required"),
//     question: z.string().min(1, "question is required"),
//   }),
// });

// export type ChatSchemaType = z.infer<typeof chatSchema.body>;

export type summarizeSchemaType = z.infer<typeof summarizeSchema.params>;