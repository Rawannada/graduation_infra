import React from 'react'
import Drop from './Drop'
import { NavLink } from 'react-router-dom'
import { Search, Plus, LibraryBig, House } from 'lucide-react';
import img from './assets/sidebar.png'
import frame from './assets/Frame.svg'
export default function Sidebar() {
    return (

        <div className="sidebar">
            <div className="d-flex flex-column contain">
                <img src={frame} alt="Sidebar Image" className="sidebar-image" />
                <div className="d-flex flex-column home">
                    <div className="user">
                        <div className="d-flex  justify-content-between align-items-center username">
                            <Drop />
                            <div className="d-flex gap-2 search"><Search size={11} /><Plus size={10.5} /> </div>

                        </div>
                        <div className="homep">

                            <NavLink to="home"><House size={20} /> Home</NavLink>
                            <NavLink to="library"><LibraryBig size={20} /> Library</NavLink>
                        </div>

                    </div>
                    <div className="priv">
                        <h3>private</h3>
                        <h4> <Plus size={20} />create folder

                        </h4>
                    </div>
                </div>
            </div>

        </div>

    )
}
