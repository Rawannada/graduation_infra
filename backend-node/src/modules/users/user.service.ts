import { NextFunction, Request, Response } from "express";
import * as UVT from "./user.validation";
import userModel, { RoleTypes } from "../../DB/models/user.model";
import { UserRepository } from "../../DB/repositories/user.repository";
import { AppError } from "../../utils/ClassError";
import { Compare, Hash } from "../../utils/hash";
import { generateOtp } from "../../service/sendEmail";
import { eventEmitter } from "../../utils/event";
import uuid4 from "uuid4";
import { GenerateToken } from "../../utils/Token";
import { RevokeTokenRepository } from "../../DB/repositories/revokeToken.repository";
import RevokeTokenModel from "../../DB/models/RevokeToken.model";
import fs from "fs";

class UserService {
  private _userModel = new UserRepository(userModel);
  private _revokeToken = new RevokeTokenRepository(RevokeTokenModel);

  signUp = async (req: Request, res: Response, next: NextFunction) => {
    const { email, password, userName }: UVT.signUpSchemaType = req.body;

    if (await this._userModel.findOne({ email }))
      throw new AppError("User already exists", 409);

    const hashedPassword = await Hash(password);
    const OTP = await generateOtp();
    const hashedOTP = await Hash(String(OTP));

    eventEmitter.emit("confirmEmail", { email, OTP });
    const user = await this._userModel.createOneUser({
      OTP: hashedOTP,
      email,
      password: hashedPassword,
      userName,
    });

    return res.status(201).json({ message: "Success", user });
  };

  confirmEmail = async (req: Request, res: Response, next: NextFunction) => {
    const { email, OTP }: UVT.confirmEmailSchemaType = req.body;

    const user = await this._userModel.findOne({
      email,
      confirmed: { $exists: false },
    });
    if (!user) throw new AppError("User Not Found or already confirmed", 409);

    if (!(await Compare(OTP, user?.OTP!)))
      throw new AppError("InValid OTP", 400);

    await this._userModel.updateOne(
      { email: user.email },
      { confirmed: true, $unset: { OTP: "" } },
    );
    return res.status(200).json({ message: "confirmed" });
  };



  signIn = async (req: Request, res: Response, next: NextFunction) => {
    const { email, password }: UVT.signInSchemaType = req.body;

    const user = await this._userModel.findOne({ email, confirmed: true });
    if (!user) throw new AppError("Email Not Found Or Not Confirmed yet", 404);

    if (!(await Compare(password, user?.password!)))
      throw new AppError("Wrong Password", 403);

    const jwtid = uuid4();

    const accessToken = await GenerateToken({
      payload: { id: user.id, email: user.email },
      signature:
        user.role == RoleTypes.admin
          ? process.env.ACCESS_ADMIN!
          : process.env.ACCESS_USER!,
      options: { expiresIn: "1d", jwtid },
    });

    const refreshToken = await GenerateToken({
      payload: { id: user.id, email: user.email },
      signature:
        user.role == RoleTypes.admin
          ? process.env.REFRESH_ADMIN!
          : process.env.REFRESH_USER!,
      options: { expiresIn: "1y", jwtid },
    });
    return res
      .status(200)
      .json({ message: "success", accessToken, refreshToken });
  };

  getProfile = async (req: Request, res: Response, next: NextFunction) => {
    return res.status(200).json({ message: "success", user: req.user });
  };

  logOut = async (req: Request, res: Response, next: NextFunction) => {
    const { flag }: UVT.logoutSchemaType = req.body;

    if (flag == UVT.flagType.all) {
      await this._userModel.updateOne(
        { _id: req?.user?._id },
        { changeCredentials: new Date() },
      );
      return res
        .status(200)
        .json({ message: "Success Logged out from all devices" });
    }
    await this._revokeToken.create({
      tokenId: req?.decoded?.jti!,
      userId: req?.user?._id!,
      expireAt: new Date(req?.decoded?.exp! * 1000),
    });

    return res
      .status(200)
      .json({ message: "User Logged Out from this device" });
  };

  refreshToken = async (req: Request, res: Response, next: NextFunction) => {
    const jwtid = uuid4();

    const accessToken = await GenerateToken({
      payload: { id: req?.user?.id, email: req?.user?.email },
      signature:
        req?.user?.role == RoleTypes.admin
          ? process.env.ACCESS_ADMIN!
          : process.env.ACCESS_USER!,
      options: { expiresIn: "1d", jwtid },
    });

    const refreshToken = await GenerateToken({
      payload: { id: req?.user?.id, email: req?.user?.email },
      signature:
        req?.user?.role == RoleTypes.admin
          ? process.env.REFRESH_ADMIN!
          : process.env.REFRESH_USER!,
      options: { expiresIn: "1y", jwtid },
    });

    await this._revokeToken.create({
      tokenId: req?.decoded?.jti!,
      userId: req?.user?._id!,
      expireAt: new Date(req?.decoded?.exp! * 1000),
    });
    return res
      .status(200)
      .json({ message: "Success", accessToken, refreshToken });
  };

  forgetPassword = async (req: Request, res: Response, next: NextFunction) => {
    const { email }: UVT.forgetPasswordSchemaType = req.body;

    const user = await this._userModel.findOne({ email });
    if (!user) throw new AppError("User Not Found", 404);

    const OTP = await generateOtp();
    const hashedOtp = await Hash(String(OTP));
    eventEmitter.emit("forgetPassword", { email, OTP });

    await this._userModel.updateOne(
      { email: user?.email },
      {
        OTP: hashedOtp,
      },
    );

    return res.status(200).json({ message: "OTP Sent to email" });
  };

  codeConfirmation = async (req: Request, res: Response, next: NextFunction) => {
    const { OTP, email } = req.body

    const user = await this._userModel.findOne({
      email,
      OTP: { $exists: true },
    });
    if (!user) throw new AppError("User Not Found", 404);

    if (!Compare(OTP, user?.OTP!)) throw new AppError("InValid OTP", 400);

    return res.status(200).json({ message: "Success" });
  };

  resetPassword = async (req: Request, res: Response, next: NextFunction) => {
    const { email, password, cPassword }: UVT.resetPasswordSchemaType =
      req.body;

    const user = await this._userModel.findOne({
      email,
      OTP: { $exists: true },
    });
    if (!user) throw new AppError("User Not Found", 404);

    const hashedPassword = await Hash(password);

    await this._userModel.updateOne(
      { email: user?.email },
      {
        password: hashedPassword,
        $unset: { OTP: "" },
      },
    );

    return res.status(200).json({ message: "Password updated" });
  };
}

export default new UserService();
