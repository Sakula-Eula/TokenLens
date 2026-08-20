import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import TrayOverviewView from "./views/TrayOverviewView.vue";

const RootComponent = window.location.pathname === "/widget" ? TrayOverviewView : App;
const app = createApp(RootComponent);
if (RootComponent === App) app.use(router);
app.mount("#app");
