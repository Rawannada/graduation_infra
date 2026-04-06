import {hash, compare} from "bcrypt"

export const Hash = async(palinText: string, saltRoud: number = Number(process.env.SALT_ROUND)) =>{
  return hash(palinText, saltRoud)
}

export const Compare = async(palinText: string, cipherText: string) =>{
  return compare(palinText, cipherText)
}