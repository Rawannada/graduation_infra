import mongoose from "mongoose";
import z from "zod";

// export const uploadSchema = {
//   body: z
//     .strictObject({
//       userId: z.string().refine(
//         (data) => {
//           return mongoose.Types.ObjectId.isValid(data);
//         },
//         {
//           message: "InValid Id",
//         },
//       ),
//     })
//     .required(),
// };

// export type uploadSchemaType = z.infer<typeof uploadSchema.body>;
