import US from "./user.service";
import * as UV from "./user.validation";
import { Router } from "express";
import { validation } from "../../middleware/validation";
import { Authentication } from "../../middleware/Authentication";
import { TokenType } from "../../utils/Token";
import { allowedExtensions, MulterLocal } from "../../middleware/Multer";

const userRouter = Router()

userRouter.post('/signUp', validation(UV.signUpSchema), US.signUp)
userRouter.patch('/confirmEmail', validation(UV.confirmEmailSchema), US.confirmEmail)
//userRouter.post('/updateProfile', Authentication(), MulterLocal({customExtensions: allowedExtensions.image}).single('image'),validation(UV.updateProfileSchema), US.updateProfile)
userRouter.post('/signIn', validation(UV.signInSchema), US.signIn)
userRouter.get('/profile', Authentication(), US.getProfile)
userRouter.post('/logout', Authentication(), validation(UV.logoutSchema), US.logOut)
userRouter.get('/refreshToken', Authentication(TokenType.refresh), US.refreshToken)
userRouter.patch('/forgetPassword', validation(UV.forgetPasswordSchema), US.forgetPassword)
userRouter.post('/confirmCode', US.codeConfirmation)
userRouter.patch('/resetPassword', validation(UV.resetPasswordSchema), US.resetPassword)




export default userRouter