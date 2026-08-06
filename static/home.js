// ===========================================
// Navbar Background on Scroll
// ===========================================

const navbar = document.querySelector(".navbar");

window.addEventListener("scroll", () => {

    if(window.scrollY > 80){

        navbar.style.background = "rgba(6,18,35,.82)";
        navbar.style.backdropFilter = "blur(40px)";
        navbar.style.boxShadow = "0 10px 40px rgba(0,0,0,.25)";

    }

    else{

        navbar.style.background = "rgba(6,18,35,.45)";
        navbar.style.boxShadow = "none";

    }

});

// ===========================================
// Reveal Animation
// ===========================================

const revealElements = document.querySelectorAll(
".feature-card,.stat-card,.step,.about-left,.preview-window,.cta-box"
);

function reveal(){

    revealElements.forEach(element=>{

        const top = element.getBoundingClientRect().top;

        if(top < window.innerHeight-120){

            element.classList.add("show");

        }

    });

}

window.addEventListener("scroll",reveal);

reveal();

// ===========================================
// Floating Cards
// ===========================================

document.querySelectorAll(".feature-card").forEach((card,index)=>{

    card.style.animation=
    `floatCard ${4+index*.4}s ease-in-out infinite`;

});

// ===========================================
// Mouse Glow
// ===========================================

const glow=document.createElement("div");

glow.className="mouse-glow";

document.body.appendChild(glow);

document.addEventListener("mousemove",(e)=>{

glow.style.left=e.clientX+"px";

glow.style.top=e.clientY+"px";

});

// ===========================================
// Counter Animation
// ===========================================

document.querySelectorAll(".stat-card h2").forEach(counter=>{

const target=counter.innerText;

if(!isNaN(parseInt(target))){

let value=0;

const end=parseInt(target);

const timer=setInterval(()=>{

value++;

counter.innerText=value+(target.includes("%")?"%":"");

if(value>=end){

clearInterval(timer);

}

},25);

}

});