/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 1.6428571428571428, "KoPercent": 98.35714285714286};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.005714285714285714, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.0, 500, 1500, "GET /api/satellites"], "isController": false}, {"data": [0.0, 500, 1500, "POST /api/alerts/:id/acknowledge"], "isController": false}, {"data": [0.0, 500, 1500, "GET /api/satellites/:id/telemetry"], "isController": false}, {"data": [0.0, 500, 1500, "GET /api/tle"], "isController": false}, {"data": [0.04, 500, 1500, "POST /api/login"], "isController": false}, {"data": [0.0, 500, 1500, "GET /api/ranking"], "isController": false}, {"data": [0.0, 500, 1500, "GET /api/alerts"], "isController": false}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 1400, 1377, 98.35714285714286, 29960.225714285698, 1003, 31241, 30436.0, 30841.0, 30925.95, 31082.92, 6.5231268142446455, 1.186070627117104, 1.2148231650211303], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["GET /api/satellites", 200, 200, 100.0, 30452.870000000006, 30023, 30907, 30475.5, 30807.7, 30849.7, 30901.94, 3.258231106332372, 0.5790996692895427, 0.5498901365198833], "isController": false}, {"data": ["POST /api/alerts/:id/acknowledge", 200, 200, 100.0, 30367.729999999992, 30009, 30784, 30330.5, 30680.4, 30734.75, 30773.96, 3.2860147213459516, 0.5840377727392219, 0.6701031192494743], "isController": false}, {"data": ["GET /api/satellites/:id/telemetry", 200, 200, 100.0, 30565.630000000005, 30028, 31070, 30682.5, 30982.4, 31017.75, 31063.94, 3.2350419746696213, 0.574978163466671, 0.6407531379907154], "isController": false}, {"data": ["GET /api/tle", 200, 200, 100.0, 30398.85499999999, 30016, 30990, 30397.5, 30692.3, 30892.65, 30962.91, 3.2474385828178023, 0.5771814668680079, 0.5258694001980937], "isController": false}, {"data": ["POST /api/login", 200, 177, 88.5, 26881.390000000003, 1003, 30347, 30177.5, 30292.0, 30316.9, 30339.98, 6.441638752898737, 1.3293743256409432, 1.5475030597784076], "isController": false}, {"data": ["GET /api/ranking", 200, 200, 100.0, 30575.425000000014, 30030, 31241, 30653.5, 30997.8, 31125.65, 31232.9, 3.2261186566441915, 0.5733921831144949, 0.5350190139368326], "isController": false}, {"data": ["GET /api/alerts", 200, 200, 100.0, 30479.679999999997, 30007, 30748, 30534.5, 30674.5, 30703.7, 30739.9, 3.307862789851477, 0.5879209255400085, 0.5453451134596936], "isController": false}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["500/Internal Server Error", 1377, 100.0, 98.35714285714286], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 1400, 1377, "500/Internal Server Error", 1377, "", "", "", "", "", "", "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": ["GET /api/satellites", 200, 200, "500/Internal Server Error", 200, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["POST /api/alerts/:id/acknowledge", 200, 200, "500/Internal Server Error", 200, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/satellites/:id/telemetry", 200, 200, "500/Internal Server Error", 200, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/tle", 200, 200, "500/Internal Server Error", 200, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["POST /api/login", 200, 177, "500/Internal Server Error", 177, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/ranking", 200, 200, "500/Internal Server Error", 200, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["GET /api/alerts", 200, 200, "500/Internal Server Error", 200, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
