import React from 'react'
import { ChevronRight } from 'lucide-react';
export default function Drop() {
  return (
    <div className="dropdown">
  <button className=" dropbtn" type="button" data-bs-toggle="dropdown" aria-expanded="false">
    username <ChevronRight  size={11} />
  </button>
  <ul className="dropdown-menu">
    <li><button className="dropdown-item" type="button">Action</button></li>
    <li><button className="dropdown-item" type="button">Another action</button></li>
    <li><button className="dropdown-item" type="button">Something else here</button></li>
  </ul>
</div>
  )
}
