import React from 'react'
import Sidebar from './SideBar'
import { Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="layout d-flex justify-content-around ">
      <Sidebar />

      <div style={{height:"698px", marginTop:"16px", width:"1284px"}} className="content  ">
        <Outlet />
      </div>
    </div>
  )
}