# Framework Locator Hints

Load only the section matching the authorized repository. These are discovery hints, not proof of
reachability or product behavior.

## Frontend

### Vue

- routes: `src/router/`, route records, `meta.title`
- menus: layout/sidebar configuration
- fields: form-item labels, rules, disabled/readonly conditions
- lists: columns, filters, pagination, empty states
- actions: click handlers, router navigation, confirmation dialogs
- permissions: route guards and permission directives/composables

### React

- routes: route objects, router creation, route components
- menus: navigation configuration
- fields: form labels, schemas, disabled/readonly conditions
- lists: column definitions, filters, pagination, empty states
- actions: event handlers, navigation, confirmation dialogs
- permissions: protected routes and authorization wrappers/hooks

For both, visibility is not enforcement. A hidden button supports only a visibility observation
until a runtime enforcement layer is connected.

## Backend

### Spring

- entries: controller mappings and request models
- enforcement: authorization annotations, validators, service guards
- states: domain/service transition methods and persisted results
- feedback: exception mapping and user-visible response contracts

### NestJS and Node routers

- entries: controllers, routers, modules, public handlers
- enforcement: guards, pipes, schemas, service checks
- states: service/domain transitions and repository writes
- feedback: filters, error mappings, returned response shapes

An endpoint declaration or exported handler alone remains `partial`; establish its caller,
enforcement point, and observable outcome before claiming alignment.

## Cross-layer triangulation

For an end-to-end finding, seek at least two distinct layers:

1. `entry`: reachable page, route, command, or public handler
2. `enforcement`: permission or validation point
3. `state`: persisted or externally observable state transition
4. `feedback`: visible result, error, retry, rollback, or navigation
5. `external`: boundary with another actor or system

Use the canonical enforcement point alone only when `evidence_coverage=enforcement-layer`.
When frontend and backend disagree, record both and classify the result as `unknown` or
`conflict` according to the calibration contract.
