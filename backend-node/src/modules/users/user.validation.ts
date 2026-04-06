import z from "zod";
import { GenderTypes, RoleTypes } from "../../DB/models/user.model";

export enum flagType {
  all = "all",
  current = "current",
}

export const signInSchema = {
  body: z
    .strictObject({
      email: z.email(),
      password: z.string(),
    })
    .required(),
};

export const signUpSchema = {
  body: signInSchema.body
    .extend({
      cPassword: z.string(),
      role: z.enum([RoleTypes.admin, RoleTypes.user]).optional(),
    })
    .required()
    .superRefine((data, ctx) => {
      if (data.password !== data.cPassword) {
        ctx.addIssue({
          code: "custom",
          path: ["cPassword"],
          message: "Password Not Match",
        });
      }
    }),
};

export const confirmEmailSchema = {
  body: z
    .strictObject({
      email: z.email(),
      OTP: z.string().min(6).max(6).trim(),
    })
    .required(),
};

export const updateProfileSchema = {
  body: z.strictObject({
    fullName: z.string().min(2).max(50).trim(),
  }).required(),
};

export const logoutSchema = {
  body: z
    .object({
      flag: z.enum(flagType),
    })
    .required(),
};


export const forgetPasswordSchema = {
  body: z.object({
    email: z.email()
  }).required()
}

export const resetPasswordSchema = {
  body:z.strictObject({
    email: z.email(),
    password: z.string().regex(/^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/),
    cPassword: z.string()
  }).required().refine((data) =>{
    return data.password === data.cPassword
  },{
    error: "Password Not match",
    path: ["cPassword"]
  })
}

export type signUpSchemaType = z.infer<typeof signUpSchema.body>;
export type signInSchemaType = z.infer<typeof signInSchema.body>;
export type confirmEmailSchemaType = z.infer<typeof confirmEmailSchema.body>;
export type logoutSchemaType = z.infer<typeof logoutSchema.body>;
export type updateProfileSchemaType = z.infer<typeof updateProfileSchema.body>;
export type forgetPasswordSchemaType = z.infer<typeof forgetPasswordSchema.body>
export type resetPasswordSchemaType = z.infer<typeof resetPasswordSchema.body>


