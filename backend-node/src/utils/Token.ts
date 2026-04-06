import jwt, { JwtPayload } from "jsonwebtoken"
import { AppError } from "./ClassError"
import { UserRepository } from "../DB/repositories/user.repository"
import userModel from "../DB/models/user.model"
import { RevokeTokenRepository } from "../DB/repositories/revokeToken.repository"
import RevokeTokenModel from "../DB/models/RevokeToken.model"

const _userModel = new UserRepository(userModel)
const _revokeToken = new RevokeTokenRepository(RevokeTokenModel)

export enum TokenType {
  access= 'access',
  refresh = 'refresh'
}

export const GenerateToken = async({payload, signature, options}: {
  payload: object,
  signature: string,
  options: jwt.SignOptions
}): Promise<string> =>{
  return jwt.sign(payload, signature, options)
}

export const VerifyToken = async({token, signature}: {
  token: string,
  signature: string
}): Promise<JwtPayload> =>{
  return jwt.verify(token, signature) as JwtPayload
}

export const Getsignature = async(tokenType: TokenType, prefix: string) =>{
  if(tokenType == TokenType.access){
    if(prefix == 'bearer')
      return process.env.ACCESS_USER
    else if(prefix == 'admin')
      return process.env.ACCESS_ADMIN
    else
      return null
  }

  if(tokenType == TokenType.refresh){
    if(prefix == 'bearer')
      return process.env.REFRESH_USER
    else if(prefix == 'admin')
      return process.env.REFRESH_ADMIN
    else
      return null
  }
  return null
}

export const decodeTokenAndFetchUser = async(token: string, signature: string) =>{
  const decoded = await VerifyToken({token, signature})
  if(!decoded)
    throw new AppError('InValid Token', 400)

    const user = await _userModel.findOne({email: decoded.email})
    if(!user){
      throw new AppError('User Not Found', 404)
    }

    if(!user.confirmed)
      throw new AppError('Please Confirm your email first', 400)

    if(await _revokeToken.findOne({tokenId: decoded?.jti!}))
      throw new AppError('Token has been revoked', 401)

    if(user?.changeCredentials?.getTime()! > decoded?.iat! * 1000)
      throw new AppError('Token has been revoked', 403)

    return {decoded, user}

}

