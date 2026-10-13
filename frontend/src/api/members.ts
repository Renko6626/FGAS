import {request} from './client'
import type {Member} from './funds'
export const membersApi={list:()=>request<Member[]>('/members'),create:(data:{name:string;note:string})=>request<Member>('/members','POST',data),update:(id:string,data:{name:string;note:string})=>request<Member>('/members/'+id,'PATCH',data)}
