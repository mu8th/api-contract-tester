// Data layer: fetch API data and insert it as plain text nodes.
// The presentation layer in index.html decorates these nodes.

async function load_specs() {
    const response = await fetch('/api/specs');
    if (!response.ok) return;
    const data = await response.json();
    const ul = document.getElementById('specs-list');
    data.forEach(spec => {
        const li = document.createElement('li');
        li.textContent = `${spec.name} (${spec.version})`;
        ul.appendChild(li);
    });
}


async function load_tests() {
    const response = await fetch('/api/tests');
    if (!response.ok) return;
    const data = await response.json();
    const tbody = document.querySelector('#tests-table tbody');
    data.forEach(test => {
        const tr = document.createElement('tr');
        [String(test.id), test.status ? 'pass' : 'fail', String(test.severity_score ?? 0)]
            .forEach(value => {
                const td = document.createElement('td');
                td.textContent = value;
                tr.appendChild(td);
            });
        tbody.appendChild(tr);
    });
}


async function load_diffs() {
    const response = await fetch('/api/results');
    if (!response.ok) return;
    const data = await response.json();
    const container = document.getElementById('diffs-container');
    data.forEach(result => {
        const div = document.createElement('div');
        div.textContent = `Drift: ${result.drift_score} | Violations: ${result.violations.length}`;
        container.appendChild(div);
    });
}


load_specs();
load_tests();
load_diffs();
