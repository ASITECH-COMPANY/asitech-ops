/**
 * Lucide icons rendered to inline SVG at build time: no icon library ships to the browser.
 */
import {
  ArrowRight,
  Boxes,
  Check,
  CircleDashed,
  Copy,
  FileText,
  GitBranch,
  CodeXml,
  Star,
  Globe,
  KeyRound,
  Languages,
  LoaderCircle,
  Lock,
  Menu,
  Moon,
  Network,
  Rocket,
  RotateCcw,
  ScrollText,
  Server,
  ShieldCheck,
  Sun,
  Terminal,
  TriangleAlert,
  Users,
  Activity,
  Scale,
  X,
  Container,
  CircleCheck,
  Bug,
  BookOpen,
  Mail,
} from "lucide";

type Attrs = Record<string, string | number>;
type Child = [string, Attrs];
type IconNode = Child[] | [string, Attrs, Child[]];

const ICONS = {
  activity: Activity,
  arrowRight: ArrowRight,
  bookOpen: BookOpen,
  boxes: Boxes,
  bug: Bug,
  check: Check,
  circleCheck: CircleCheck,
  circleDashed: CircleDashed,
  container: Container,
  copy: Copy,
  fileText: FileText,
  gitBranch: GitBranch,
  code: CodeXml,
  globe: Globe,
  keyRound: KeyRound,
  languages: Languages,
  loader: LoaderCircle,
  lock: Lock,
  mail: Mail,
  menu: Menu,
  moon: Moon,
  network: Network,
  rocket: Rocket,
  rotateCcw: RotateCcw,
  scale: Scale,
  scrollText: ScrollText,
  server: Server,
  shieldCheck: ShieldCheck,
  star: Star,
  sun: Sun,
  terminal: Terminal,
  alert: TriangleAlert,
  users: Users,
  x: X,
} as const;

export type IconName = keyof typeof ICONS;

function attrs(values: Attrs): string {
  return Object.entries(values)
    .map(([key, value]) => `${key}="${String(value).replace(/"/g, "&quot;")}"`)
    .join(" ");
}

function children(node: IconNode): Child[] {
  // Lucide exports either the children list or a full ["svg", attrs, children] node.
  if (typeof node[0] === "string") return (node as [string, Attrs, Child[]])[2];
  return node as Child[];
}

export function icon(name: IconName, className = "size-5"): string {
  const inner = children(ICONS[name] as unknown as IconNode)
    .map(([tag, values]) => `<${tag} ${attrs(values)}/>`)
    .join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" class="${className}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${inner}</svg>`
  );
}
