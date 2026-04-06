import React from 'react'
import Sidebar from './Sidebar'
import { Outlet } from 'react-router-dom'


export default function Layout() {
  return (
    <div className="layout">
      <div className="container-fluid"><div className="row">
        <div className="col-2"><Sidebar /></div>
        <div className="col-10">
          <div className="content ">
            <Outlet />
          </div>
        </div>
      </div></div>


    </div>
  )
}
