import { NextFunction, Request, Response } from "express";
import { AppError } from "../utils/ClassError";
import { decodeTokenAndFetchUser, Getsignature, TokenType } from "../utils/Token";

export const Authentication = (tokenType: TokenType = TokenType.access) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const { authorization } = req.headers;
    const [prefix, token] = authorization?.split(" ") || [];

    if (!prefix || !token) throw new AppError("InValid token", 400);

    const signature = await Getsignature(tokenType, prefix);
    if (!signature) throw new AppError("InValid Signature", 400);

    const decoded = await decodeTokenAndFetchUser(token, signature);
    if (!decoded) throw new AppError("InValid Token", 400);

    req.user = decoded?.user;
    req.decoded = decoded?.decoded;

    return next();
  };
};