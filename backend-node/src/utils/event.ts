import {EventEmitter} from "events"
import { sendEmail } from "../service/sendEmail"

export const eventEmitter = new EventEmitter()

eventEmitter.on('confirmEmail', async(data) =>{
  const {email, OTP} = data
  return sendEmail({to: email, subject: 'Confirm Email', html: `<h1>${OTP}</h1>`})
})

eventEmitter.on('forgetPassword', (data) =>{
  const {email, OTP} = data
  return sendEmail({to: email, subject: 'Forget Password', html: `<h1>${OTP}</h1>`})
})